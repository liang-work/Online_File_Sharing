from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory
from flask_login import login_required, current_user
from models import File
from forms import ProfileForm
from utils import get_config_dict
from datetime import datetime

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    if current_user.is_authenticated:
        files = File.query.filter_by(user_id=current_user.id).all()
    else:
        # 过滤过期的公开文件
        files = File.query.filter_by(is_public=True).filter(
            (File.expiry_time.is_(None)) | (File.expiry_time > datetime.utcnow())
        ).all()
    return render_template('index.html', files=files, config=get_config_dict())

@main_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    from models import db
    form = ProfileForm()
    if form.validate_on_submit():
        current_user.nickname = form.nickname.data
        current_user.avatar_url = form.avatar_url.data
        current_user.language = form.language.data
        current_user.theme = form.theme.data
        db.session.commit()
        flash('个人资料已更新')
        return redirect(url_for('main.profile'))

    # 预填充表单
    if request.method == 'GET':
        form.nickname.data = current_user.nickname
        form.avatar_url.data = current_user.avatar_url
        form.language.data = current_user.language
        form.theme.data = current_user.theme

    return render_template('profile.html', form=form, config=get_config_dict())

@main_bp.route('/toggle_theme')
@login_required
def toggle_theme():
    from models import db
    current_user.theme = 'dark' if current_user.theme == 'light' else 'light'
    db.session.commit()
    return redirect(request.referrer or url_for('main.index'))

@main_bp.route('/set_language/<lang>')
@login_required
def set_language(lang):
    from models import db
    if lang in ['zh', 'en']:
        current_user.language = lang
        db.session.commit()
    return redirect(request.referrer or url_for('main.index'))

@main_bp.route("/bg.jpeg")
def bg_jpeg():
    return send_from_directory('static', 'bg.jpeg')
