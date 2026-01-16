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
    if request.method == 'POST':
        # 处理通过JavaScript发送的请求（没有CSRF token）
        files = request.files.getlist('files')
        if not files:
            flash('请选择要上传的文件')
            return redirect(request.url)

        # 获取表单参数
        share_type = request.form.get('share_type', 'link_only')
        allow_view = request.form.get('allow_view', 'true').lower() == 'true'
        allow_download = request.form.get('allow_download', 'true').lower() == 'true'
        allow_edit = request.form.get('allow_edit', 'false').lower() == 'true'
        password = request.form.get('password') or None
        expiry_type = request.form.get('expiry_type', 'never')
        expiry_hours = request.form.get('expiry_hours')
        custom_expiry = request.form.get('custom_expiry')
        allowed_users = request.form.get('allowed_users')

        # 检查用户限制
        current_files_count = current_user.get_total_files_count()
        current_total_size = current_user.get_total_files_size()

        uploaded_files = []
        skipped_files = []

        for file in files:
            if file and file.filename:
                # 检查单文件大小限制
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)

                if file_size > current_user.max_file_size:
                    skipped_files.append(f'文件 "{file.filename}" 超过单文件大小限制 ({current_user.max_file_size // (1024*1024)}MB)')
                    continue

                # 检查总文件数量限制
                if current_files_count >= current_user.max_total_files:
                    skipped_files.append('已达到总文件数量限制，无法上传更多文件')
                    break

                # 检查总文件大小限制
                if current_total_size + file_size > current_user.max_total_size:
                    skipped_files.append('上传后将超过总文件大小限制，无法上传')
                    break

                raw_filename = file.filename  # 完全原始的文件名
                filename = secure_filename(file.filename)
                unique_filename = str(uuid.uuid4()) + '_' + filename
                filepath = os.path.join('uploads', unique_filename)
                file.save(filepath)

                # 处理过期时间
                expiry_time = None
                if expiry_type == 'hours' and expiry_hours:
                    try:
                        expiry_time = datetime.utcnow() + timedelta(hours=int(expiry_hours))
                    except ValueError:
                        skipped_files.append(f'文件 "{file.filename}" 的过期时间格式错误')
                        continue
                elif expiry_type == 'custom' and custom_expiry:
                    try:
                        expiry_time = datetime.strptime(custom_expiry, '%Y-%m-%d %H:%M')
                    except ValueError:
                        skipped_files.append(f'文件 "{file.filename}" 的自定义过期时间格式错误')
                        continue

                # 处理允许用户列表
                allowed_users_json = None
                if share_type == 'specified_users' and allowed_users:
                    allowed_users_list = [u.strip() for u in allowed_users.split('\n') if u.strip()]
                    allowed_users_json = json.dumps(allowed_users_list)

                new_file = File(
                    filename=unique_filename,
                    original_filename=filename,
                    raw_filename=raw_filename,
                    filepath=filepath,
                    user_id=current_user.id,
                    is_public=(share_type == 'public'),
                    share_type=share_type,
                    allow_view=allow_view,
                    allow_download=allow_download,
                    allow_edit=allow_edit,
                    password=password,
                    expiry_time=expiry_time,
                    allowed_users=allowed_users_json
                )
                db.session.add(new_file)
                uploaded_files.append(filename)

                current_files_count += 1
                current_total_size += file_size

        # 一次性提交所有文件
        try:
            db.session.commit()
            if uploaded_files:
                flash(f'成功上传 {len(uploaded_files)} 个文件')
            if skipped_files:
                for msg in skipped_files:
                    flash(msg)
        except Exception as e:
            db.session.rollback()
            flash(f'上传失败: {str(e)}')

        return redirect(url_for('main.index'))

    # GET请求显示表单
    form = UploadForm()
    return render_template('files/upload.html', form=form, config=get_config_dict())

@files_bp.route('/file/<file_id>')
def view_file(file_id):
    file = File.query.get_or_404(file_id)

    # 检查权限
    can_access = False

    if file.share_type == 'public':
        can_access = True
    elif file.share_type == 'link_only':
        can_access = True  # 链接分享允许任何人访问
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

@files_bp.route('/preview/<file_id>')
def preview_file(file_id):
    """预览文件（只允许页面内联显示，禁止外部引用和直接下载）"""
    from flask import request, abort

    file = File.query.get_or_404(file_id)

    # 检查权限
    can_access = False

    if file.share_type == 'public':
        can_access = True
    elif file.share_type == 'link_only':
        can_access = True  # 链接分享允许任何人访问
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
        abort(403)  # 无权访问

    # 检查过期时间
    if file.expiry_time and datetime.utcnow() > file.expiry_time:
        abort(410)  # 文件已过期

    # 检查查看权限
    if not file.allow_view:
        abort(403)  # 不允许查看

    # 检查Referer头，防止外部引用
    referer = request.headers.get('Referer', '')
    if referer:
        from urllib.parse import urlparse
        parsed_referer = urlparse(referer)
        # 只允许来自同一域名的引用
        if parsed_referer.netloc and parsed_referer.netloc != request.host:
            abort(403)  # 禁止外部域名引用

    # 检查Accept头，确保是浏览器正常请求
    accept = request.headers.get('Accept', '')
    # 如果Accept头包含浏览器常见的MIME类型，说明是正常预览请求
    if not any(mime in accept for mime in ['text/html', 'image/', 'video/', 'audio/', 'application/pdf', '*/*']):
        abort(403)  # 可疑的请求

    # 返回文件内容用于预览，设置安全头
    response = send_from_directory('uploads', file.filename)

    # 设置安全头，防止缓存和外部引用
    response.headers['Cache-Control'] = 'private, no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'

    return response

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
                return render_template('files/share.html', form=form, file=file, config=get_config_dict())

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

    return render_template('files/share.html', form=form, file=file, config=get_config_dict())

@files_bp.route('/file/<file_id>/details')
def file_details(file_id):
    file = File.query.get_or_404(file_id)

    # 检查权限
    can_access = False

    if file.share_type == 'public':
        can_access = True
    elif file.share_type == 'link_only':
        can_access = True  # 链接分享允许任何人访问
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

    # 检查查看权限
    if not file.allow_view:
        flash('此文件不允许查看')
        return redirect(url_for('main.index'))

    # 获取文件大小
    try:
        file_size = os.path.getsize(file.filepath)
    except:
        file_size = 0

    # 获取文件扩展名
    _, ext = os.path.splitext(file.original_filename.lower())

    # 判断是否可以预览（只要有查看权限就可以预览）
    can_preview = False
    preview_type = None
    preview_content = None

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
        # 读取文本文件内容进行预览
        try:
            with open(file.filepath, 'r', encoding='utf-8', errors='ignore') as f:
                preview_content = f.read(10240)  # 最多读取10KB
        except:
            preview_content = "无法读取文件内容"

    return render_template('files/file_details.html', file=file, file_size=file_size,
                         can_preview=can_preview, preview_type=preview_type, preview_content=preview_content,
                         current_time=datetime.utcnow(), config=get_config_dict())
