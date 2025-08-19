# categories.py
from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db, Category, Item

categories_bp = Blueprint('categories', __name__)

@categories_bp.route('/categories', methods=['GET', 'POST'])
@login_required
def manage_categories():
    if request.method == 'POST':
        name = (request.form.get('name') or '').strip()
        if not name:
            flash('Category name is required', 'error')
        else:
            exists = Category.query.filter_by(user_id=current_user.id, name=name).first()
            if exists:
                flash('That category already exists.', 'error')
            else:
                c = Category(user_id=current_user.id, name=name)
                db.session.add(c)
                db.session.commit()
                flash('Category created.', 'success')
        return redirect(url_for('categories.manage_categories'))

    cats = Category.query.filter_by(user_id=current_user.id).order_by(Category.name.asc()).all()
    return render_template('categories.html', categories=cats)

@categories_bp.route('/categories/<int:cat_id>/delete', methods=['POST'])
@login_required
def delete_category(cat_id):
    cat = Category.query.filter_by(id=cat_id, user_id=current_user.id).first_or_404()
    Item.query.filter_by(user_id=current_user.id, category_id=cat.id).update({Item.category_id: None})
    db.session.delete(cat)
    db.session.commit()
    flash('Category deleted.', 'success')
    return redirect(url_for('categories.manage_categories'))
