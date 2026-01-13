from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory, abort, jsonify
from flask_login import login_required, current_user
from models import File, db
from forms import UploadForm, ShareForm
from utils import get_config_dict
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
import json
import uuid

files_bp = Blueprint('files', __name__)

@files_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    form = UploadForm()
    if form.validate_on_submit():
        files = request.files.getlist('files')

        # 检查用户限制
        current_files_count = current_user.get_total_files_count()
        current_total_size = current_user.get_total_files_size()

        for file in files:
            if file and file.filename:
                # 检查单文件大小限制
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)

                if file_size > current_user.max_file_size:
                    flash(f'文件 "{file.filename}" 超过单文件大小限制 ({current_user.max_file_size // (1024*1024)}MB)')
                    continue

                # 检查总文件数量限制
                if current_files_count >= current_user.max_total_files:
                    flash('已达到总文件数量限制，无法上传更多文件')
                    break

                # 检查总文件大小限制
                if current_total_size + file_size > current_user.max_total_size:
                    flash('上传后将超过总文件大小限制，无法上传')
                    break

                filename = secure_filename(file.filename)
                unique_filename = str(uuid.uuid4()) + '_' + filename
                filepath = os.path.join('uploads', unique_filename)
                file.save(filepath)

                # 处理过期时间
                expiry_time = None
                if form.expiry_type.data == 'hours' and form.expiry_hours.data:
                    expiry_time = datetime.utcnow() + timedelta(hours=int(form.expiry_hours.data))
                elif form.expiry_type.data == 'custom' and form.custom_expiry.data:
                    try:
                        expiry_time = datetime.strptime(form.custom_expiry.data, '%Y-%m-%d %H:%M')
                    except ValueError:
                        flash(f'文件 "{file.filename}" 的自定义过期时间格式错误')
                        continue

                # 处理允许用户列表
                allowed_users_json = None
                if form.share_type.data == 'specified_users' and form.allowed_users.data:
                    allowed_users = [u.strip() for u in form.allowed_users.data.split('\n') if u.strip()]
                    allowed_users_json = json.dumps(allowed_users)

                new_file = File(
                    filename=unique_filename,
                    original_filename=filename,
                    filepath=filepath,
                    user_id=current_user.id,
                    is_public=(form.share_type.data == 'public'),
                    share_type=form.share_type.data,
                    allow_view=form.allow_view.data,
                    allow_download=form.allow_download.data,
                    allow_edit=form.allow_edit.data,
                    password=form.password.data if form.password.data else None,
                    expiry_time=expiry_time,
                    allowed_users=allowed_users_json
                )
                db.session.add(new_file)

                current_files_count += 1
                current_total_size += file_size

        db.session.commit()
        flash('文件上传成功')
        return redirect(url_for('main.index'))
    return render_template('files/upload.html', form=form)

@files_bp.route('/file/<file_id>')
def view_file(file_id):
    file = File.query.get_or_404(file_id)

    # 检查权限
    can_access = False

    if file.share_type == 'public':
        can_access = True
    elif file.share_type == 'link_only':
        can_access = current_user.is_authenticated
    elif file.share_type == 'specified_users':
        if current_user.is_authenticated:
            if current_user.role == 'admin' or current_user.id == file.user_id:
                can_access = True
            elif file.allowed_users:
                try:
                    allowed_users = json.loads(file.allowed_users)
                    can_access = current_user.username in allowed_users
                except:
                    can_access = False
        else:
            can_access = False

    if not can_access:
        if not current_user.is_authenticated:
            flash('需要登录才能访问此文件')
            return redirect(url_for('auth.login'))
        else:
            flash('无权访问此文件')
            return redirect(url_for('main.index'))

    # 检查过期时间
    if file.expiry_time and datetime.utcnow() > file.expiry_time:
        flash('文件已过期')
        return redirect(url_for('main.index'))

    # 检查下载权限
    if not file.allow_download:
        flash('此文件不允许下载')
        return redirect(url_for('main.index'))

    return send_from_directory('uploads', file.filename, as_attachment=True, download_name=file.original_filename)

@files_bp.route('/share/<file_id>', methods=['GET', 'POST'])
@login_required
def share_file(file_id):
    file = File.query.get_or_404(file_id)
    if file.user_id != current_user.id and current_user.role != 'admin':
        flash('无权修改此文件分享设置')
        return redirect(url_for('main.index'))

    form = ShareForm()
    if form.validate_on_submit():
        # 处理过期时间
        expiry_time = None
        if form.expiry_type.data == 'hours' and form.expiry_hours.data:
            expiry_time = datetime.utcnow() + timedelta(hours=int(form.expiry_hours.data))
        elif form.expiry_type.data == 'custom' and form.custom_expiry.data:
            try:
                expiry_time = datetime.strptime(form.custom_expiry.data, '%Y-%m-%d %H:%M')
            except ValueError:
                flash('自定义过期时间格式错误')
                return render_template('files/share.html', form=form, file=file)

        # 处理允许用户列表
        allowed_users_json = None
        if form.share_type.data == 'specified_users' and form.allowed_users.data:
            allowed_users = [u.strip() for u in form.allowed_users.data.split('\n') if u.strip()]
            allowed_users_json = json.dumps(allowed_users)

        # 更新文件设置
        file.is_public = (form.share_type.data == 'public')
        file.share_type = form.share_type.data
        file.allow_view = form.allow_view.data
        file.allow_download = form.allow_download.data
        file.allow_edit = form.allow_edit.data
        file.password = form.password.data if form.password.data else None
        file.expiry_time = expiry_time
        file.allowed_users = allowed_users_json

        db.session.commit()
        flash('分享设置已更新')
        return redirect(url_for('main.index'))

    # 预填充表单
    form.share_type.data = file.share_type
    form.allow_view.data = file.allow_view
    form.allow_download.data = file.allow_download
    form.allow_edit.data = file.allow_edit
    form.password.data = file.password

    # 处理过期时间预填充
    if file.expiry_time:
        now = datetime.utcnow()
        if file.expiry_time > now:
            remaining_hours = int((file.expiry_time - now).total_seconds() / 3600)
            if remaining_hours <= 720:
                form.expiry_type.data = 'hours'
                form.expiry_hours.data = str(min(remaining_hours, 720))
            else:
                form.expiry_type.data = 'custom'
                form.custom_expiry.data = file.expiry_time.strftime('%Y-%m-%d %H:%M')
    else:
        form.expiry_type.data = 'never'

    # 处理允许用户列表
    if file.allowed_users:
        try:
            allowed_users_list = json.loads(file.allowed_users)
            form.allowed_users.data = '\n'.join(allowed_users_list)
        except:
            pass

    return render_template('files/share.html', form=form, file=file)

@files_bp.route('/file/<file_id>/details')
def file_details(file_id):
    file = File.query.get_or_404(file_id)

    # 检查权限
    can_access = False

    if file.share_type == 'public':
        can_access = True
    elif file.share_type == 'link_only':
        can_access = current_user.is_authenticated
    elif file.share_type == 'specified_users':
        if current_user.is_authenticated:
            if current_user.role == 'admin' or current_user.id == file.user_id:
                can_access = True
            elif file.allowed_users:
                try:
                    allowed_users = json.loads(file.allowed_users)
                    can_access = current_user.username in allowed_users
                except:
                    can_access = False
        else:
            can_access = False

    if not can_access:
        if not current_user.is_authenticated:
            flash('需要登录才能查看文件详情')
            return redirect(url_for('auth.login'))
        else:
            flash('无权查看此文件详情')
            return redirect(url_for('main.index'))

    # 检查过期时间
    if file.expiry_time and datetime.utcnow() > file.expiry_time:
        flash('文件已过期')
        return redirect(url_for('main.index'))

    # 获取文件大小
    try:
        file_size = os.path.getsize(file.filepath)
    except:
        file_size = 0

    # 获取文件扩展名
    _, ext = os.path.splitext(file.original_filename.lower())

    # 判断是否可以预览
    can_preview = False
    preview_type = None

    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']:
        can_preview = True
        preview_type = 'image'
    elif ext in ['.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm']:
        can_preview = True
        preview_type = 'video'
    elif ext in ['.mp3', '.wav', '.ogg', '.aac', '.flac']:
        can_preview = True
        preview_type = 'audio'
    elif ext in ['.pdf']:
        can_preview = True
        preview_type = 'pdf'
    elif ext in ['.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml']:
        can_preview = True
        preview_type = 'text'

    return render_template('files/file_details.html', file=file, file_size=file_size,
                         can_preview=can_preview, preview_type=preview_type,
                         current_time=datetime.utcnow())
