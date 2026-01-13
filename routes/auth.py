from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, login_required, logout_user, current_user
from models import User, db
from forms import LoginForm, RegisterForm
from utils import is_registration_allowed, get_config_value
from datetime import datetime, timedelta

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('main.index'))
        flash('用户名或密码错误')
    return render_template('auth/login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    # 检查是否允许注册
    if not is_registration_allowed():
        flash('当前系统不允许用户注册')
        return redirect(url_for('auth.login'))

    form = RegisterForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user:
            flash('用户名已存在')
        else:
            new_user = User()
            new_user.username = form.username.data
            new_user.set_password(form.password.data)

            # 设置默认限制
            default_file_size = int(get_config_value('default_max_file_size', '1024')) * 1024 * 1024
            default_total_files = int(get_config_value('default_max_total_files', '100'))
            default_total_size = int(get_config_value('default_max_total_size', '10')) * 1024 * 1024 * 1024

            new_user.max_file_size = default_file_size
            new_user.max_total_files = default_total_files
            new_user.max_total_size = default_total_size

            # 设置默认主题和语言
            default_theme = get_config_value('default_theme', 'light')
            default_language = get_config_value('default_language', 'zh')

            new_user.theme = default_theme
            new_user.language = default_language

            db.session.add(new_user)
            db.session.commit()
            flash('注册成功，请登录')
            return redirect(url_for('auth.login'))
    return render_template('auth/register.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))
