import json
from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from app.models import Procurement, Item, AvailableStock
from app import db

inventory_bp = Blueprint('inventory', __name__, url_prefix='/inventory')

@inventory_bp.before_request
def require_login():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))

@inventory_bp.route('/')
def index():
    tab = request.args.get('tab', 'active') # 'active' or 'archive'
    
    if tab == 'archive':
        procurements = Procurement.query.filter_by(status='Archived').order_by(Procurement.created_at.desc()).all()
    else:
        procurements = Procurement.query.filter(Procurement.status != 'Archived').order_by(Procurement.created_at.desc()).all()
    
    total_awarded = 0
    total_complete_items = 0
    total_pending_items = 0
    surplus_items = []
    allocatable_items = []

    all_procs = Procurement.query.all()
    for p in all_procs:
        if p.status == 'Awarded':
            total_awarded += 1
            
        total_target = sum(item.target_qty for item in p.items) if p.items else 0
        if total_target > 0:
            total_current = sum(min(item.current_qty, item.target_qty) for item in p.items)
            p.progress = int((total_current / total_target) * 100)
            if p.progress == 100:
                total_complete_items += 1
            else:
                total_pending_items += 1
        else:
            p.progress = 0
            total_pending_items += 1

        for item in p.items:
            surplus_quantity = item.current_qty - item.target_qty
            if surplus_quantity > 0:
                surplus_items.append({
                    'source_type': 'surplus',
                    'source_id': item.id,
                    'name': item.name,
                    'unit': item.unit,
                    'expiration_date': item.expiration_date,
                    'quantity': surplus_quantity,
                    'procurement': p,
                })
            remaining_quantity = item.target_qty - item.current_qty
            if p.status != 'Archived' and remaining_quantity > 0:
                allocatable_items.append({
                    'item': item,
                    'remaining_quantity': remaining_quantity,
                })

    manual_stocks = AvailableStock.query.filter(AvailableStock.quantity > 0).all()
    for stock in manual_stocks:
        surplus_items.append({
            'source_type': 'manual',
            'source_id': stock.id,
            'name': stock.name,
            'unit': stock.unit,
            'expiration_date': stock.expiration_date,
            'quantity': stock.quantity,
            'procurement': None,
        })
    surplus_items.sort(
        key=lambda stock: stock['expiration_date'] or date.max
    )

    stats = {
        'pending': total_pending_items,
        'complete': total_complete_items,
        'awarded': total_awarded
    }

    today = date.today()
    return render_template(
        'inventory/index.html',
        procurements=procurements,
        stats=stats,
        current_tab=tab,
        surplus_items=surplus_items,
        manual_stocks=manual_stocks,
        allocatable_items=allocatable_items,
        today=today,
        warning_cutoff=today + timedelta(days=30),
    )

@inventory_bp.route('/available-stock/add', methods=['POST'])
def add_available_stock():
    name = request.form.get('name', '').strip()
    unit = request.form.get('unit', '').strip()
    try:
        quantity = int(request.form.get('quantity', ''))
    except ValueError:
        flash("Please enter a valid stock quantity.", "danger")
        return redirect(url_for('inventory.index'))

    expiration_date_value = request.form.get('expiration_date', '')
    try:
        expiration_date = date.fromisoformat(expiration_date_value) if expiration_date_value else None
    except ValueError:
        flash("Please enter a valid expiration date.", "danger")
        return redirect(url_for('inventory.index'))

    if not name:
        flash("Please enter an item name.", "danger")
        return redirect(url_for('inventory.index'))
    if quantity <= 0:
        flash("Stock quantity must be greater than zero.", "danger")
        return redirect(url_for('inventory.index'))

    stock = AvailableStock(
        name=name,
        quantity=quantity,
        unit=unit or None,
        expiration_date=expiration_date,
    )
    db.session.add(stock)
    db.session.commit()
    flash(f"'{stock.name}' added to available excess stock.", "success")
    return redirect(url_for('inventory.index'))

@inventory_bp.route('/available-stock/<int:stock_id>/update', methods=['POST'])
def update_available_stock(stock_id):
    stock = AvailableStock.query.get_or_404(stock_id)
    try:
        quantity = int(request.form.get('quantity', ''))
    except ValueError:
        flash("Please enter a valid stock quantity.", "danger")
        return redirect(url_for('inventory.index'))

    expiration_date = stock.expiration_date
    if 'expiration_date' in request.form:
        expiration_date_value = request.form.get('expiration_date', '')
        try:
            expiration_date = date.fromisoformat(expiration_date_value) if expiration_date_value else None
        except ValueError:
            flash("Please enter a valid expiration date.", "danger")
            return redirect(url_for('inventory.index'))

    if quantity < 0:
        flash("Stock quantity cannot be negative.", "danger")
        return redirect(url_for('inventory.index'))

    if quantity == 0:
        db.session.delete(stock)
    else:
        stock.quantity = quantity
        stock.expiration_date = expiration_date
    db.session.commit()
    flash(f"Available stock for '{stock.name}' updated.", "success")
    return redirect(url_for('inventory.index'))

@inventory_bp.route('/available-stock/<int:stock_id>/edit', methods=['POST'])
def edit_available_stock(stock_id):
    stock = AvailableStock.query.get_or_404(stock_id)
    name = request.form.get('name', '').strip()
    unit = request.form.get('unit', '').strip()
    try:
        quantity = int(request.form.get('quantity', ''))
    except ValueError:
        flash("Please enter a valid stock quantity.", "danger")
        return redirect(url_for('inventory.index'))

    expiration_date_value = request.form.get('expiration_date', '')
    try:
        expiration_date = date.fromisoformat(expiration_date_value) if expiration_date_value else None
    except ValueError:
        flash("Please enter a valid expiration date.", "danger")
        return redirect(url_for('inventory.index'))

    if not name:
        flash("Please enter an item name.", "danger")
        return redirect(url_for('inventory.index'))
    if quantity <= 0:
        flash("Stock quantity must be greater than zero. Delete the stock to remove it.", "danger")
        return redirect(url_for('inventory.index'))

    stock.name = name
    stock.quantity = quantity
    stock.unit = unit or None
    stock.expiration_date = expiration_date
    db.session.commit()
    flash(f"Available stock '{stock.name}' updated.", "success")
    return redirect(url_for('inventory.index'))

@inventory_bp.route('/available-stock/<int:stock_id>/delete', methods=['POST'])
def delete_available_stock(stock_id):
    stock = AvailableStock.query.get_or_404(stock_id)
    name = stock.name
    db.session.delete(stock)
    db.session.commit()
    flash(f"Available stock '{name}' deleted.", "info")
    return redirect(url_for('inventory.index'))

@inventory_bp.route('/surplus/<int:item_id>/remove', methods=['POST'])
def remove_surplus(item_id):
    item = Item.query.get_or_404(item_id)
    target_quantity = max(item.target_qty, 0)
    if item.current_qty <= target_quantity:
        flash(f"'{item.name}' no longer has excess stock to remove.", "warning")
        return redirect(url_for('inventory.index'))

    item.current_qty = target_quantity
    db.session.commit()
    flash(f"Excess stock for '{item.name}' removed; procurement quantity was preserved.", "info")
    return redirect(url_for('inventory.index'))

@inventory_bp.route('/available-stock/<string:source_type>/<int:source_id>/allocate', methods=['POST'])
def allocate_available_stock(source_type, source_id):
    if source_type == 'surplus':
        source = Item.query.get_or_404(source_id)
        available_quantity = max(source.current_qty - source.target_qty, 0)
    elif source_type == 'manual':
        source = AvailableStock.query.get_or_404(source_id)
        available_quantity = source.quantity
    else:
        flash("Invalid stock source.", "danger")
        return redirect(url_for('inventory.index'))

    try:
        destination_id = int(request.form.get('destination_item_id', ''))
        quantity = int(request.form.get('quantity', ''))
    except ValueError:
        flash("Choose a procurement item and enter a valid quantity.", "danger")
        return redirect(url_for('inventory.index'))

    destination = Item.query.get_or_404(destination_id)
    remaining_quantity = destination.target_qty - destination.current_qty
    if destination.procurement.status == 'Archived':
        flash("Stock cannot be allocated to an archived procurement.", "danger")
        return redirect(url_for('inventory.index'))
    if quantity <= 0:
        flash("Allocation quantity must be greater than zero.", "danger")
        return redirect(url_for('inventory.index'))
    if quantity > available_quantity:
        flash("Allocation exceeds the available stock quantity.", "danger")
        return redirect(url_for('inventory.index'))
    if quantity > remaining_quantity:
        flash("Allocation exceeds the procurement item's remaining target quantity.", "danger")
        return redirect(url_for('inventory.index'))
    if source_type == 'surplus' and source.id == destination.id:
        flash("Choose a different procurement item for this stock.", "danger")
        return redirect(url_for('inventory.index'))

    if source_type == 'surplus':
        source.current_qty -= quantity
        source_expiration_date = source.expiration_date
    else:
        source.quantity -= quantity
        source_expiration_date = source.expiration_date
        if source.quantity == 0:
            db.session.delete(source)
    destination.current_qty += quantity
    if source_expiration_date and (
        destination.expiration_date is None
        or source_expiration_date < destination.expiration_date
    ):
        destination.expiration_date = source_expiration_date
    db.session.commit()
    flash(f"Allocated {quantity} {destination.unit or 'unit'} of '{destination.name}' to '{destination.procurement.title}'.", "success")
    return redirect(url_for('inventory.index'))

@inventory_bp.route('/surplus/<int:item_id>', methods=['POST'])
def update_surplus(item_id):
    item = Item.query.get_or_404(item_id)
    try:
        surplus_quantity = int(request.form.get('surplus_qty', ''))
    except ValueError:
        flash("Please enter a valid excess stock quantity.", "danger")
        return redirect(url_for('inventory.index'))

    expiration_date = item.expiration_date
    if 'expiration_date' in request.form:
        expiration_date_value = request.form.get('expiration_date', '')
        try:
            expiration_date = date.fromisoformat(expiration_date_value) if expiration_date_value else None
        except ValueError:
            flash("Please enter a valid expiration date.", "danger")
            return redirect(url_for('inventory.index'))

    if surplus_quantity < 0:
        flash("Excess stock quantity cannot be negative.", "danger")
        return redirect(url_for('inventory.index'))

    target_quantity = max(item.target_qty, 0)
    current_surplus = max(item.current_qty - target_quantity, 0)
    if current_surplus == 0:
        flash(f"'{item.name}' no longer has excess stock to update.", "warning")
        return redirect(url_for('inventory.index'))

    item.current_qty = target_quantity + surplus_quantity
    item.expiration_date = expiration_date
    db.session.commit()
    flash(f"Excess stock for '{item.name}' updated.", "success")
    return redirect(url_for('inventory.index'))

@inventory_bp.route('/send_to_inventory', methods=['POST'])
def send_to_inventory():
    raw_json = request.form.get('parsed_json')
    if not raw_json:
        flash("No scan data available to send.", "danger")
        return redirect(url_for('inventory.index'))

    try:
        data = json.loads(raw_json)
        metadata = data.get('metadata', {})
        items = data.get('items', [])

        # 1. Create the Procurement Folder from extracted metadata
        new_proc = Procurement(
            title=metadata.get('procurement_title', 'Scanned Bid Notice'),
            abc=metadata.get('abc', 0.0),
            pre_bid_date=metadata.get('pre_bid_conference_date', 'N/A'),
            place_of_bidding=metadata.get('place_of_bidding', 'N/A'),
            municipality=metadata.get('municipality', 'N/A'),
            agency=metadata.get('agency_requested', 'N/A'),
            status='Ongoing'
        )
        db.session.add(new_proc)
        db.session.flush()  # Flushes session to generate new_proc.id before commit

        # 2. Iterate through items and attach them to the procurement
        for idx, item in enumerate(items, start=1):
            new_item = Item(
                procurement_id=new_proc.id,
                code=f"ITEM-{idx:03d}",
                name=item.get('item_name', 'Unnamed Item'),
                category=item.get('description', ''),
                price=float(item.get('price') or 0.0),
                unit=item.get('unit', 'pcs'),
                target_qty=int(item.get('quantity') or 1),
                current_qty=0
            )
            db.session.add(new_item)

        db.session.commit()
        flash(f"Successfully saved procurement notice '{new_proc.title}' and {len(items)} items to Inventory!", "success")
        return redirect(url_for('inventory.view_procurement', procurement_id=new_proc.id))

    except Exception as e:
        db.session.rollback()
        flash(f"Error transferring scan to inventory: {str(e)}", "danger")
        return redirect(url_for('inventory.index'))

@inventory_bp.route('/add_procurement', methods=['GET', 'POST'])
def add_procurement():
    if request.method == 'POST':
        title = request.form.get('title')
        abc = request.form.get('abc')
        pre_bid_date = request.form.get('pre_bid_date')
        place_of_bidding = request.form.get('place_of_bidding')
        municipality = request.form.get('municipality')
        agency = request.form.get('agency')

        new_proc = Procurement(
            title=title, abc=abc, pre_bid_date=pre_bid_date,
            place_of_bidding=place_of_bidding, municipality=municipality,
            agency=agency, status='Ongoing'
        )
        db.session.add(new_proc)
        db.session.commit()
        
        flash('New Procurement folder created successfully.', 'success')
        return redirect(url_for('inventory.index'))
    
    return redirect(url_for('inventory.index'))

@inventory_bp.route('/<int:procurement_id>/edit', methods=['POST'])
def edit_procurement(procurement_id):
    procurement = Procurement.query.get_or_404(procurement_id)
    title = request.form.get('title', '').strip()
    if not title:
        flash("Procurement name cannot be empty.", "danger")
        return redirect(url_for('inventory.view_procurement', procurement_id=procurement.id))

    procurement.title = title
    procurement.pre_bid_date = request.form.get('pre_bid_date', '').strip() or None
    procurement.municipality = request.form.get('municipality', '').strip() or None
    procurement.place_of_bidding = request.form.get('place_of_bidding', '').strip() or None
    db.session.commit()
    flash("Procurement details updated successfully.", "success")
    return redirect(url_for('inventory.view_procurement', procurement_id=procurement.id))

@inventory_bp.route('/<int:procurement_id>')
def view_procurement(procurement_id):
    procurement = Procurement.query.get_or_404(procurement_id)
    today = date.today()
    warning_cutoff = today + timedelta(days=30)
    expiring_items = [
        item for item in procurement.items
        if item.current_qty > 0
        and item.expiration_date is not None
        and item.expiration_date <= warning_cutoff
    ]
    expiring_items.sort(key=lambda item: item.expiration_date)
    return render_template(
        'inventory/view.html',
        procurement=procurement,
        today=today,
        warning_cutoff=warning_cutoff,
        expiring_items=expiring_items,
    )


@inventory_bp.route('/items/<int:item_id>/delivery-check', methods=['POST'])
def toggle_delivery_check(item_id):
    item = Item.query.get_or_404(item_id)
    item.delivery_checked = 'delivery_checked' in request.form
    db.session.commit()
    flash(f"Delivery check updated for '{item.name}'.", "success")
    return redirect(url_for('inventory.view_procurement', procurement_id=item.procurement_id))


@inventory_bp.route('/print/<int:procurement_id>')
def print_procurement(procurement_id):
    procurement = Procurement.query.get_or_404(procurement_id)
    return render_template('inventory/print.html', procurement=procurement)

@inventory_bp.route('/<int:procurement_id>/add_item', methods=['POST'])
def add_item(procurement_id):
    procurement = Procurement.query.get_or_404(procurement_id)
    expiration_date_value = request.form.get('expiration_date', '')
    try:
        expiration_date = date.fromisoformat(expiration_date_value) if expiration_date_value else None
    except ValueError:
        flash("Please enter a valid expiration date.", "danger")
        return redirect(url_for('inventory.view_procurement', procurement_id=procurement.id))
    
    new_item = Item(
        procurement_id=procurement.id,
        code=request.form.get('code'),
        name=request.form.get('name'),
        category=request.form.get('category'),
        price=float(request.form.get('price') or 0.0),
        unit=request.form.get('unit'),
        target_qty=int(request.form.get('target_qty') or 1),
        current_qty=int(request.form.get('current_qty') or 0),
        expiration_date=expiration_date,
    )
    db.session.add(new_item)
    db.session.commit()
    
    flash(f"Item '{new_item.name}' added to folder.", "success")
    return redirect(url_for('inventory.view_procurement', procurement_id=procurement.id))

@inventory_bp.route('/edit_item/<int:item_id>', methods=['POST'])
def edit_item(item_id):
    item = Item.query.get_or_404(item_id)
    expiration_date_value = request.form.get('expiration_date', '')
    try:
        expiration_date = date.fromisoformat(expiration_date_value) if expiration_date_value else None
    except ValueError:
        flash("Please enter a valid expiration date.", "danger")
        return redirect(url_for('inventory.view_procurement', procurement_id=item.procurement_id))
    
    item.code = request.form.get('code')
    item.name = request.form.get('name')
    item.category = request.form.get('category')
    item.price = float(request.form.get('price') or 0.0)
    item.unit = request.form.get('unit')
    item.target_qty = int(request.form.get('target_qty') or 1)
    item.current_qty = int(request.form.get('current_qty') or 0)
    item.expiration_date = expiration_date
    
    db.session.commit()
    flash(f"Item '{item.name}' updated successfully.", "success")
    return redirect(url_for('inventory.view_procurement', procurement_id=item.procurement_id))

@inventory_bp.route('/delete_item/<int:item_id>', methods=['POST'])
def delete_item(item_id):
    item = Item.query.get_or_404(item_id)
    proc_id = item.procurement_id
    db.session.delete(item)
    db.session.commit()
    flash("Item removed from inventory.", "info")
    return redirect(url_for('inventory.view_procurement', procurement_id=proc_id))

@inventory_bp.route('/update_status/<int:procurement_id>/<string:status>', methods=['POST'])
def update_status(procurement_id, status):
    procurement = Procurement.query.get_or_404(procurement_id)
    if status in ['Ongoing', 'Awarded', 'Archived']:
        procurement.status = status
        db.session.commit()
        flash(f"Procurement status updated to: {status}", "success")
    return redirect(url_for('inventory.view_procurement', procurement_id=procurement.id))

@inventory_bp.route('/delete_procurement/<int:procurement_id>', methods=['POST'])
def delete_procurement(procurement_id):
    procurement = Procurement.query.get_or_404(procurement_id)
    db.session.delete(procurement)
    db.session.commit()
    flash("Procurement folder permanently deleted.", "info")
    return redirect(url_for('inventory.index', tab='archive'))
