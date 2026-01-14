from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from models import User, File, db
from forms import ConfigForm, UserLimitForm, RegisterForm
from utils import get_config_dict
from flask_wtf import FlaskForm
from wtforms import StringField, SelectField, SubmitField, BooleanField, PasswordField
from wtforms.validators import DataRequired, Length
import os

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/config', methods=['GET', 'POST'])
@login_required
def admin_config():
    if current_user.role != 'admin':
        flash('无权访问此页面')
        return redirect(url_for('main.index'))

    form = ConfigForm()

    # 获取当前配置
    config_dict = get_config_dict()

    if request.method == 'GET':
        # 预填充表单
        form.allow_registration.data = config_dict.get('allow_registration', 'true').lower() == 'true'
        form.default_max_file_size.data = config_dict.get('default_max_file_size', '1024')
        form.default_max_total_files.data = config_dict.get('default_max_total_files', '100')
        form.default_max_total_size.data = config_dict.get('default_max_total_size', '10')
        form.background_image.data = config_dict.get('background_image', '')
        form.default_theme.data = config_dict.get('default_theme', 'light')
        form.default_language.data = config_dict.get('default_language', 'zh')
        form.primary_color.data = config_dict.get('primary_color', '#667eea')

    if form.validate_on_submit():
        from models import Config
        # 保存配置
        configs = [
            ('allow_registration', str(form.allow_registration.data), '是否允许用户注册'),
            ('default_max_file_size', form.default_max_file_size.data, '默认单文件大小限制(MB)'),
            ('default_max_total_files', form.default_max_total_files.data, '默认总文件数量限制'),
            ('default_max_total_size', form.default_max_total_size.data, '默认总文件大小限制(GB)'),
            ('background_image', form.background_image.data or '', '系统背景图片URL'),
            ('default_theme', form.default_theme.data, '默认主题设置'),
            ('default_language', form.default_language.data, '默认语言设置'),
            ('primary_color', form.primary_color.data, '主题色设置')
        ]

        for key, value, desc in configs:
            config = Config.query.filter_by(key=key).first()
            if not config:
                config = Config(key=key, value=value, description=desc)
                db.session.add(config)
            else:
                config.value = value

        db.session.commit()
        flash('配置已保存')
        return redirect(url_for('admin.admin_config'))

    return render_template('admin/admin_config.html', form=form, config=config_dict)

@admin_bp.route('/users')
@login_required
def admin_users():
    if current_user.role != 'admin':
        flash('无权访问此页面')
        return redirect(url_for('main.index'))

    users = User.query.all()
    return render_template('admin/admin_users.html', users=users, config=get_config_dict())

@admin_bp.route('/user/<int:user_id>/limits', methods=['GET', 'POST'])
@login_required
def admin_user_limits(user_id):
    if current_user.role != 'admin':
        flash('无权访问此页面')
        return redirect(url_for('main.index'))

    user = User.query.get_or_404(user_id)
    form = UserLimitForm()

    if request.method == 'GET':
        # 预填充表单
        form.max_file_size.data = str(user.max_file_size // (1024*1024))  # 转换为MB
        form.max_total_files.data = str(user.max_total_files)
        form.max_total_size.data = str(user.max_total_size // (1024*1024*1024))  # 转换为GB

    if form.validate_on_submit():
        try:
            if form.max_file_size.data:
                user.max_file_size = int(form.max_file_size.data) * 1024 * 1024  # MB to bytes
            if form.max_total_files.data:
                user.max_total_files = int(form.max_total_files.data)
            if form.max_total_size.data:
                user.max_total_size = int(form.max_total_size.data) * 1024 * 1024 * 1024  # GB to bytes
            db.session.commit()
            flash('用户限制已更新')
            return redirect(url_for('admin.admin_users'))
        except ValueError:
            flash('输入格式错误，请输入有效的数字')

    return render_template('admin/user_limits.html', form=form, user=user, config=get_config_dict())

@admin_bp.route('/user/create', methods=['GET', 'POST'])
@login_required
def admin_create_user():
    if current_user.role != 'admin':
        flash('无权访问此页面')
        return redirect(url_for('main.index'))

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
            config_dict = get_config_dict()
            default_file_size = int(config_dict.get('default_max_file_size', '1024')) * 1024 * 1024
            default_total_files = int(config_dict.get('default_max_total_files', '100'))
            default_total_size = int(config_dict.get('default_max_total_size', '10')) * 1024 * 1024 * 1024

            new_user.max_file_size = default_file_size
            new_user.max_total_files = default_total_files
            new_user.max_total_size = default_total_size

            db.session.add(new_user)
            db.session.commit()
            flash(f'用户 "{form.username.data}" 创建成功')
            return redirect(url_for('admin.admin_users'))
    return render_template('admin/create_user.html', form=form, config=get_config_dict())

@admin_bp.route('/user/<int:user_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_user(user_id):
    if current_user.role != 'admin':
        flash('无权访问此页面')
        return redirect(url_for('main.index'))

    user = User.query.get_or_404(user_id)

    class EditUserForm(FlaskForm):
        username = StringField('用户名', validators=[DataRequired(), Length(min=4, max=150)])
        role = SelectField('角色', choices=[('user', '普通用户'), ('admin', '管理员')])
        submit = SubmitField('保存修改')

    form = EditUserForm()
    if form.validate_on_submit():
        # 检查用户名是否已被其他用户使用
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user and existing_user.id != user.id:
            flash('用户名已存在')
        else:
            user.username = form.username.data
            user.role = form.role.data
            db.session.commit()
            flash('用户信息已更新')
            return redirect(url_for('admin.admin_users'))

    # 预填充表单
    if request.method == 'GET':
        form.username.data = user.username
        form.role.data = user.role

    return render_template('admin/edit_user.html', form=form, user=user, config=get_config_dict())

@admin_bp.route('/user/<int:user_id>/delete', methods=['POST'])
@login_required
def admin_delete_user(user_id):
    if current_user.role != 'admin':
        flash('无权访问此页面')
        return redirect(url_for('main.index'))

    user = User.query.get_or_404(user_id)

    # 不允许删除自己
    if user.id == current_user.id:
        flash('不能删除自己的账号')
        return redirect(url_for('admin.admin_users'))

    # 删除用户的文件
    files = File.query.filter_by(user_id=user.id).all()
    for file in files:
        try:
            os.remove(file.filepath)
        except:
            pass

    # 删除数据库记录
    File.query.filter_by(user_id=user.id).delete()
    db.session.delete(user)
    db.session.commit()

    flash(f'用户 "{user.username}" 及其所有文件已删除')
    return redirect(url_for('admin.admin_users'))

@admin_bp.route('/files')
@login_required
def admin_files():
    if current_user.role != 'admin':
        flash('无权访问此页面')
        return redirect(url_for('main.index'))

    files = File.query.all()
    return render_template('admin/admin_files.html', files=files, config=get_config_dict())

@admin_bp.route('/file/<file_id>/edit', methods=['GET', 'POST'])
@login_required
def admin_edit_file(file_id):
    if current_user.role != 'admin':
        flash('无权访问此页面')
        return redirect(url_for('main.index'))

    file = File.query.get_or_404(file_id)

    class EditFileForm(FlaskForm):
        original_filename = StringField('文件名', validators=[DataRequired()])
        share_type = SelectField('分享类型', choices=[
            ('public', '公开分享'),
            ('link_only', '链接分享'),
            ('specified_users', '指定用户')
        ])
        allow_view = BooleanField('允许查看')
        allow_download = BooleanField('允许下载')
        allow_edit = BooleanField('允许编辑')
        password = PasswordField('访问密码')
        submit = SubmitField('保存修改')

    form = EditFileForm()
    if form.validate_on_submit():
        file.original_filename = form.original_filename.data
        file.share_type = form.share_type.data
        file.allow_view = form.allow_view.data
        file.allow_download = form.allow_download.data
        file.allow_edit = form.allow_edit.data
        file.password = form.password.data if form.password.data else None
        file.is_public = (form.share_type.data == 'public')

        db.session.commit()
        flash('文件信息已更新')
        return redirect(url_for('admin.admin_files'))

    # 预填充表单
    if request.method == 'GET':
        form.original_filename.data = file.original_filename
        form.share_type.data = file.share_type
        form.allow_view.data = file.allow_view
        form.allow_download.data = file.allow_download
        form.allow_edit.data = file.allow_edit
        form.password.data = file.password

    return render_template('admin/edit_file.html', form=form, file=file, config=get_config_dict())

@admin_bp.route('/statistics')
@login_required
def admin_statistics():
    if current_user.role != 'admin':
        flash('无权访问此页面')
        return redirect(url_for('main.index'))

    # 获取统计数据
    from models import User, File
    from datetime import datetime, timedelta

    # 用户统计
    total_users = User.query.count()
    admin_users = User.query.filter_by(role='admin').count()
    regular_users = total_users - admin_users

    # 新用户统计（最近30天）
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    new_users_30d = User.query.filter(User.created_at >= thirty_days_ago).count()

    # 文件统计
    total_files = File.query.count()
    total_file_size = 0
    for file in File.query.all():
        try:
            if os.path.exists(file.filepath):
                total_file_size += os.path.getsize(file.filepath)
        except:
            pass

    # 文件类型统计
    file_types = {}
    for file in File.query.all():
        ext = os.path.splitext(file.original_filename.lower())[1]
        if ext:
            file_types[ext] = file_types.get(ext, 0) + 1

    # 分享类型统计
    share_types = {
        'public': File.query.filter_by(share_type='public').count(),
        'link_only': File.query.filter_by(share_type='link_only').count(),
        'specified_users': File.query.filter_by(share_type='specified_users').count()
    }

    # 最近文件上传统计（最近7天）
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    recent_files = File.query.filter(File.upload_time >= seven_days_ago).count()

    # 存储空间使用统计（GB）
    total_size_gb = total_file_size / (1024 * 1024 * 1024)

    return render_template('admin/admin_statistics.html',
                         total_users=total_users,
                         admin_users=admin_users,
                         regular_users=regular_users,
                         new_users_30d=new_users_30d,
                         total_files=total_files,
                         total_size_gb=round(total_size_gb, 2),
                         file_types=file_types,
                         share_types=share_types,
                         recent_files=recent_files,
                         config=get_config_dict())

@admin_bp.route('/file/<file_id>/delete', methods=['POST'])
@login_required
def admin_delete_file(file_id):
    if current_user.role != 'admin':
        flash('无权访问此页面')
        return redirect(url_for('main.index'))

    file = File.query.get_or_404(file_id)

    # 删除文件
    try:
        os.remove(file.filepath)
    except:
        pass

    # 删除数据库记录
    db.session.delete(file)
    db.session.commit()

    flash(f'文件 "{file.original_filename}" 已删除')
    return redirect(url_for('admin.admin_files'))
